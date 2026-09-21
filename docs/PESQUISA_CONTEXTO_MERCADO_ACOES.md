# Contexto de Mercado e Enquadramento de Ações na Pesquisa Quantitativa
> **Documento de Research Quantitativo & Buy-Side Portfolio Management**  
> **Repositório**: `iitauquant` (Fundo LASTRO & Laboratório Momentum ATR — Desafio Quant AI 2026)  
> **Data de Referência**: 2026-09-21  
> **Classificação**: Documento Institucional de Alocação e Pesquisa / Modo Paper-Only  

---

## 1. Sumário Executivo & Cenário Macroeconômico (Setembro/2026)

Este documento estabelece o enquadramento sistemático das principais ações e clusters de ativos cobertos no repositório (`config/momentum_universe.json`) à luz do ambiente macroeconômico global e doméstico vigente em **setembro de 2026**.

A estrutura do fundo **LASTRO** (multi-sleeve) e do **Laboratório Momentum ATR** foi construída sobre premissas de ceticismo estatístico, ausência de viés de sobrevivência (*survivorship bias*), execução causal sem vazamento temporal (*look-ahead bias*, execução em $t+1$ no Open) e preservação estrita de capital via *shadow mode*.

### Principais Vetores Macroeconômicos:
1. **Federal Reserve Restritivo (Fed Funds entre 3,75% e 4,00%)**:
   - A inflação resiliente acima da meta de 2% nos EUA sustentou as taxas de juros em patamar elevado, gerando pressão constante sobre a taxa de desconto (*equity duration*) e penalizando empresas de múltiplos esticados sem geração imediata de fluxo de caixa livre (*Free Cash Flow*).
2. **Ciclo de Afrouxamento Gradual no Brasil (Selic a 13,75%)**:
   - O Copom manteve cortes graduais na taxa Selic, estreitando o diferencial de juros (*carry trade*) com o mercado norte-americano. Essa dinâmica pressiona a moeda (USD/BRL) e impõe inclinação íngreme na curva longa de juros locais (DIs futuros e NTN-Bs), afetando diretamente setores de consumo cíclico, alavancados e imobiliário.
3. **Superciclo de CAPEX em Inteligência Artificial ($2,7 trilhões em 2026)**:
   - A expansão contínua de infraestrutura de data centers, aceleradores gráficos e capacidade energética impulsiona fornecedores primários (semicondutores e energia industrial), enquanto os *hyperscalers* enfrentam maior exigência por retorno incremental sobre capital investido (*ROIC*).
4. **Dispersão em Commodities e Comércio Internacional**:
   - O minério de ferro permanece sob pressão estrutural decorrente da desaceleração imobiliária e da produção de aço na China, enquanto metais da transição energética (cobre e níquel) e petróleo mantêm prêmios de risco geopolítico e demanda física.

```
                              ┌──────────────────────────────────────────────┐
                              │      MERCADO FINANCEIRO RECENTE (2026)       │
                              │  - Fed Funds restritivo (3,75%-4,00%)        │
                              │  - Copom a 13,75% & Curva longa íngreme      │
                              │  - IA Capex Wave ($2,7T) & Dispersão Real    │
                              └──────────────────────┬───────────────────────┘
                                                     │
                         ┌───────────────────────────┴───────────────────────────┐
                         ▼                                                       ▼
        ┌───────────────────────────────────┐                   ┌───────────────────────────────────┐
        │   FUNDO LASTRO (MULTI-SLEEVE)     │                   │     LABORATÓRIO MOMENTUM ATR      │
        │                                   │                   │                                   │
        │ • Sleeve 1: Fama-French 5         │                   │ • Universo Global Leaders & B3    │
        │   (SMB, HML, RMW Novy-Marx, CMA)  │                   │ • Filtro EMA 21 / EMA 200         │
        │ • Sleeve 2: Small Caps + Overlay  │                   │ • Volatilidade ATR & Trailing     │
        │   BAA10Y / NFCI (De-risking BIL)  │                   │ • Execução estrita no Open t+1    │
        │ • Sleeve 3: T-Bills BIL (Safe)    │                   │ • Zero Repainting / Paper-Only    │
        └───────────────────────────────────┘                   └───────────────────────────────────┘
```

---

## 2. Enquadramento de Ações nos Motores de Pesquisa

### 2.1. Cluster Big Tech & Semicondutores (`global_leaders`)

#### NVIDIA (`NVDA`)
* **Contexto de Mercado**: Capitalização de mercado consolidada acima de \$5,3 trilhões, ramp industrial das arquiteturas Blackwell/Rubin e consolidação no ecossistema de software e modelos de linguagem de código aberto (negociações reportadas envolvendo Hugging Face por cerca de \$13 bilhões).
* **Decomposição Fatorial Fama-French (Sleeve 1)**:
  - **$RMW$ (Rentabilidade Operacional de Novy-Marx)**: *Z-score fortemente positivo*. Margens brutas superiores a 70% e $GP/TA$ no percentil mais alto do universo global.
  - **$CMA$ (Investimento / Expansão de Ativos)**: *Z-score penalizado (negativo)*. O crescimento vertiginoso do balanço e capex aloca a ação no grupo "Aggressive Investment", diminuindo sua nota combinada.
  - **$HML$ (Valor)**: *Z-score negativo*. Multiplos P/L e EV/EBITDA elevados.
* **Comportamento no Laboratório Momentum ATR**:
  - Força relativa 12-1 no topo do ranking transversal; cotação sustentada acima da EMA 21 e EMA 200 diárias.
  - **Diretriz de Risco**: Devido ao ATR elevado, o motor exige bandas de trailing stop adaptativas para prevenir encerramentos precipitados em dias de correção por volatilidade técnica.

#### MICROSOFT (`MSFT`)
* **Contexto de Mercado**: Azure crescendo entre 41% e 43% com conversão comprovada de capex em receita contratada (*backlog*) empresarial; atração de capital institucional de longo prazo.
* **Decomposição Fatorial Fama-French (Sleeve 1)**:
  - **$RMW$**: *Z-score extremamente alto*. Qualidade de balanço AAA com alavancagem líquida negativa e previsibilidade de caixa.
  - **Sensibilidade Macroeconômica**: Exposição à *equity duration*. Taxas do Fed em 3,75%–4,00% atuam como âncora nos múltiplos, exigindo crescimento contínuo do EPS para sustentar retornos adicionais.
* **Comportamento no Laboratório Momentum ATR**:
  - Volatilidade significativamente menor que a média do setor tecnológico (`SMH`), desempenhando papel de estabilizador de drawdown dentro da cesta acionária.

#### APPLE (`AAPL`)
* **Contexto de Mercado**: Anúncio da linha iPhone 18 Pro e novos dispositivos com hardware dedicado a IA sob o comando de John Ternus; projetos de servidores privados corporativos de IA com silício próprio.
* **Decomposição Fatorial Fama-French (Sleeve 1)**:
  - **$CMA$ (Investimento)**: *Z-score favorável*. A estrutura produtiva fabless/asset-light evita expansão agressiva de capital fixo imobilizado, qualificando-a positivamente no fator investimento conservador.
  - **$RMW$**: Robusto, beneficiado por programas contínuos de recompra de ações (*buybacks*), que reduzem o patrimônio contábil e elevam o retorno sobre o capital.
* **Comportamento no Laboratório Momentum ATR**:
  - Comportamento de baixa correlação com o cluster de semicondutores, atuando como amortecedor técnico em dias de realização em inteligência artificial pura.

---

### 2.2. Cluster Blue Chips B3 (`survivor_baseline`)

#### PETROBRAS (`PETR4.SA`)
* **Contexto de Mercado**: Cotações internacionais do petróleo sustentadas por risco geopolítico no Oriente Médio, combinadas à adesão da estatal a programas federais de desconto no diesel (abatimento de até R$ 1,00/L) para mitigar repasses de volatilidade ao mercado interno.
* **Decomposição Fatorial (Sleeve 1 - B3)**:
  - **$HML$ (Valor)**: *Z-score positivo extremo*. Múltiplos comprimidos (P/L e EV/EBITDA baixos), dividend yield atrativo e geração substancial de fluxo de caixa livre.
  - **$RMW$**: Custos de extração (*lifting cost*) competitivos no pré-sal garantem lucratividade operacional elevada.
  - **Governança & Risco de Cauda**: O desconto em relação a pares internacionais decorre de risco de agência regulatória. O filtro point-in-time com lag de 3 meses protege a estratégia contra vazamentos de anúncios imediatos.
* **Comportamento no Laboratório Momentum ATR**:
  - Alta correlação com as tendências do barril de petróleo Brent; cruzamentos de médias móveis identificam inflexões cíclicas da commodity.

#### VALE (`VALE3.SA`)
* **Contexto de Mercado**: Fraqueza da demanda chinesa no setor imobiliário pressionando o preço do minério de ferro e elevação em custos de frete marítimo, contrabalançada pela divisão de Metais Básicos (cobre para redes elétricas e data centers).
* **Decomposição Fatorial (Sleeve 1 - B3)**:
  - **$HML$**: Multiplos descontados historicamente.
  - **$WML$ (Momentum)**: *Z-score deprimido*. A tendência técnica reflete os cortes sucessivos nas estimativas de produção de aço na Ásia.
* **Comportamento no Laboratório Momentum ATR**:
  - Negociada abaixo da EMA 200 diária em fases baixistas do minério de ferro. No modelo algorítmico, isso gera desclassificação ou sinal neutro/venda, impedindo a alocação de risco em ativos em tendência de queda secular.

#### WEG (`WEGE3.SA`)
* **Contexto de Mercado**: Expansão acelerada de carteira de pedidos para transformadores de grande porte e sistemas de subestação atendendo à demanda energética de data centers de IA e transição industrial no exterior.
* **Decomposição Fatorial (Sleeve 1 - B3)**:
  - **$RMW$**: *Z-score no topo do mercado brasileiro*. Retorno sobre o capital investido (ROIC) recorrentemente acima de 25%.
  - **$HML$**: *Penalizada no fator Valor*. Múltiplos persistentemente altos devido ao prêmio de consistência e governança corporativa.
* **Comportamento no Laboratório Momentum ATR**:
  - Tendência de alta sólida com volatilidade moderada, servindo como núcleo de preservação de capital na carteira de ações locais.

---

### 2.3. Cluster Small Caps e Universo Distressed (`adverse_distressed`)

#### Small Caps (Sleeve 2 do LASTRO)
* **Vulnerabilidade Estrutural**:
  - Empresas de menor capitalização enfrentam custo financeiro elevado com juros altos (Fed Funds a 3,75%–4,00% e Selic a 13,75%), devido à predominância de dívidas com taxas flutuantes.
* **Mecanismo de Proteção do Fundo**:
  - O **Sleeve 2** aplica um composto 50/50 de Momentum 12-1 e Reversão de 1M, mas é submetido ao **Overlay de Regime Macro** baseado no spread de crédito `BAA10Y` e no índice financeiro `NFCI`:
    $$\text{Alocação S2} = 33,33\% \times \Big(1 - 0,25 \times \text{Eixos Ativos}\Big)$$
  - Em estresse pleno (2 eixos ativos), 50% da carteira de Small Caps migra preventivamente para `BIL`.

#### Universo Distressed (`AMER3.SA`, `OIBR3.SA`, `GOLL4.SA`)
* **Função Metodológica Inegociável**:
  - Mapeadas formalmente em `config/momentum_universe.json` sob o status `adverse_distressed`.
  - **Prevenção do Viés de Sobrevivência**: Modelos ingênuos que excluem empresas falidas ou em recuperação judicial produzem métricas infladas. O repositório exige que esses ativos façam parte da base de teste para certificar que o motor algorítmico resiste a suspensões de negociação, grupamentos extremos e perdas superiores a 90% sem quebrar a consistência das séries de retornos.

---

### 2.4. Instrumentos de Refúgio e Descorrelação

#### OURO (`GLD`)
* **Papel na Pesquisa**: Ativo do universo `global_leaders` com correlação neutra em relação a índices acionários tradicionais. Serve como barômetro de risco geopolítico e desdolarização soberana, ativando posições de proteção em momentos de aceleração inflacionária.

#### T-BILLS CURTOS (`BIL` - Sleeve 3)
* **Papel no Fundo LASTRO**:
  - Alocação estratégica passiva de 33,33% da carteira, absorvendo também o capital desinvestido do Sleeve 2 em momentos de estresse de crédito.
  - **Isolamento de Risco de Duration**: Como verificado no diagnóstico do ponto cego de 2022, ETFs de duration intermediária (como `SHY`, de 1-3 anos) sofreram desvalorização com o choque de taxas de juros. O `BIL` (duration ~0,1 ano) é o único refúgio que garante rendimento nominal monetário imediato sem risco de marcação a mercado.

---

## 3. Matriz Quantitativa Consolidada de Ativos

| Ticker | Universo no Repositório | Fatores Dominantes (Fama-French) | Sinal Momentum ATR | Sensibilidade Macroeconômica | Função no Portfólio `iitauquant` |
|---|---|---|---|---|---|
| **`NVDA`** | `global_leaders` | $RMW$ (+), $CMA$ (-), $HML$ (-) | Compra / Força Relativa Top | Capex de IA / Semicondutores | Motor de alfa de momentum; trailing stop via ATR |
| **`MSFT`** | `global_leaders` | $RMW$ (+), Balanço AAA | Tendência Moderada / Alta Qualidade | Taxa de Desconto / Nuvem | Exposição defensiva em Tech; duration moderada |
| **`AAPL`** | `global_leaders` | $CMA$ (+), $RMW$ (+) via Buybacks | Consolidação / Resiliente | Ciclo de Consumo / Silício | Candidata de baixa volatilidade no Top 50 |
| **`PETR4.SA`** | `survivor_baseline` | $HML$ (+), $RMW$ (+), Risco Político | Dependente do Brent | Petróleo / Câmbio / Subsídios | Screening de Valor no mercado doméstico |
| **`VALE3.SA`** | `survivor_baseline` | $HML$ (+), $WML$ (-) | Abaixo da EMA 200 (Neutro/Venda) | China / Minério de Ferro / Cobre | Filtro de exclusão no momentum; valor de longo prazo |
| **`WEGE3.SA`** | `survivor_baseline` | $RMW$ (+), $CMA$ (+), $HML$ (-) | Tendência Positiva Consistente | Eletrificação / CAPEX Energia | Estabilizador de drawdown no universo local |
| **`Small Caps`** | Sleeve 2 LASTRO | Momentum 12-1 / Reversão 1M | Cíclico / Alta Dispersão | Custo de Capital / BAA10Y / NFCI | Objeto do overlay macro de de-risking para BIL |
| **`AMER3.SA`** | `adverse_distressed` | Múltiplos e Balanço Distorcidos | Rejeitado por Liquidez / Risco | Selic Alta / Recuperação Judicial | Auditoria contra viés de sobrevivência |
| **`GLD`** | `global_leaders` | Não aplicável (Refúgio Real) | Momentum Positivo / Máximas | Desdolarização / Risco Geopolítico | Descorrelacionador no laboratório Momentum ATR |
| **`BIL`** | Sleeve 3 LASTRO | Taxa Livre de Risco (Duration ~0) | Carregamento Positivo Puro | Fed Funds (3,75%–4,00%) | Âncora de capital e refúgio em estresse macro |

---

## 4. Diretrizes de Governança e Execução

1. **Protocolo Causal $t+1$ Inviolável**: Nenhuma decisão fundamentada no noticiário ou em preços pode ser executada no mesmo instante de sua observação. Todo sinal observado em $t$ é executado no preço de abertura (`Open`) de $t+1$, incorporando custos operacionais de corretagem e slippage.
2. **Preservação do Shadow Mode**: Os modelos de overlay de crédito e de-risking permanecem formalmente com `governanca.aprovado=false` e `shadow_mode=true` até que a auditoria independente fora da amostra (OOS) com Deflated Sharpe Ratio (DSR) e PBO seja homologada.
3. **Trilha Auditável de GenAI**: Conforme os requisitos do edital, esta pesquisa e seu registro de contextualização foram adicionados e preservados no arquivo `log_uso_genai.csv`.
