# Relatório Técnico Interno — Fundo Sistemático Multi-Sleeve
### Documento de trabalho da equipe · Desafio Quant AI 2026

> **Natureza deste documento.** Este é o *know-how* de desenvolvimento das três carteiras — não a entrega de 5 páginas do challenge. Ele reúne o raciocínio de decisão (antes, durante e depois de cada escolha), a fundamentação teórica, a construção quantitativa e o plano de testes. A tradução para o relatório final de 5 páginas é a última seção, tratada aqui como etapa posterior.

---

## 0. Visão geral e tese central do fundo

O fundo é **uma única estratégia sistemática** composta por três *sleeves* (módulos) que se combinam num portfólio consolidado. Essa arquitetura não é estética: o edital exige *uma proposta central clara* com subcomponentes coerentes, avaliada sobre *um modelo final consolidado*. Duas ou três carteiras soltas violariam isso e não caberiam no limite de 5 páginas com qualidade.

**Tese central:** combinar dois motores de retorno em renda variável pouco correlacionados entre si — um *fundamentalista* (Factor Investing) e um *técnico* (Small Caps) — mais uma âncora de renda fixa que também serve de refúgio tático. A diversificação entre lógicas de retorno diferentes é o argumento de investimento, mais forte do que qualquer uma das carteiras isolada.

| Sleeve | Natureza | Motor de retorno | Reage a sinal de curto prazo? |
|---|---|---|---|
| 1 — Factor Investing | Fundamentalista | Prêmios de fator (Fama-French) | Não — aposta estrutural anual |
| 2 — Small Caps | Técnica / macro | Momentum, reversão, regime de crédito | Sim — tático mensal |
| 3 — Renda Fixa | Âncora | Carrego de T-bill + refúgio | Reativo ao sinal do Sleeve 2 |

**Estrutura de pesos:** base estratégica 33/33/33. Único desvio tático permitido: o peso do Sleeve 2 migra integralmente para o Sleeve 3 quando o sinal de regime de crédito acende. O Sleeve 1 nunca é afetado por gatilho — é a perna estável do fundo.

**Régua de avaliação comum:** os três sleeves e o fundo consolidado são validados pela mesma regressão contra os 5 fatores de Fama-French + momentum. Usar a mesma lente analítica nos três é, ao mesmo tempo, prova de coerência metodológica e economia de espaço no relatório.

---

## 1. Sleeve 1 — Factor Investing (5 fatores)

### 1.1. Fundamentação teórica (o "porquê")

A estratégia compra sistematicamente características que décadas de literatura associam a prêmio de retorno de longo prazo. O modelo de referência é o Fama-French de 5 fatores. Cada fator tem uma justificativa econômica que sustenta a tese perante a banca:

- **Tamanho (SMB):** empresas menores são menos líquidas e mais arriscadas; o mercado paga um prêmio para compensar esse risco (Banz, 1981).
- **Valor (HML):** o mercado tende a exagerar o otimismo com empresas "da moda" e o pessimismo com empresas baratas; quando a distorção corrige, quem comprou barato ganha o reajuste.
- **Rentabilidade (RMW):** empresas genuinamente mais lucrativas sustentam a vantagem por mais tempo do que o mercado precifica (Novy-Marx).
- **Investimento (CMA):** empresas que expandem o ativo de forma agressiva tendem a superinvestir — má alocação de capital que cobra o preço depois; crescimento conservador prediz retorno melhor.

**Por que 4 fatores no ranking, não 5.** O fator *Mercado* mede o retorno de estar exposto à bolsa como um todo — não varia entre ações dentro de um portfólio 100% comprado em ações, logo não serve como critério de seleção. Ele entra na *análise* (a regressão final mede a exposição da carteira aos 5 fatores, incluindo Mercado, como o beta), não na *seleção*. É assim que fundos quant tratam esse fator.

### 1.2. Processo de decisão — antes de construir

A decisão estrutural mais importante foi **stock picking (Caminho A) vs. alocação sobre fatores prontos (Caminho B)**. Escolhemos o Caminho A (seleção de ações individuais) porque a equipe quis a abordagem fundamentalista literal. Consequência assumida: dependência de dados fundamentalistas históricos, que são a parte frágil do pipeline. Se em algum momento o acesso a base institucional (WRDS/Compustat/Bloomberg) se confirmar, o Caminho A ganha robustez; sem isso, opera-se com as limitações de fonte gratuita descritas abaixo.

**Universo escolhido:** S&P 500. Grande, líquido, dado acessível.

### 1.3. Construção quantitativa (passo a passo)

**Fase 1 — Universo.** Lista de tickers do S&P 500 atual. *Limitação declarada:* é a composição de hoje, não a histórica — empresas que saíram do índice não aparecem, o que infla o resultado (viés de sobrevivência).

**Fase 2 — Coleta de dados.**
- Preços: em lote, todos os tickers, ajustados por dividendo/desdobramento.
- Fundamentos: empresa por empresa (não há endpoint em lote). Por empresa: valor de mercado, patrimônio líquido, ativo total (ano atual e anterior), receita, custo da receita, lucro bruto.
- Cuidados operacionais: pausa a cada ~20 tickers (rate limit) e cache por empresa em disco (se travar na 300, não se perde as 299 anteriores).
- Limite realista: fontes gratuitas dão ~4 anos de balanço anual por empresa — isso define o tamanho máximo do backtest.

**Fase 3 — Cálculo dos 4 fatores brutos.**
| Fator | Fórmula | Direção |
|---|---|---|
| Tamanho | valor de mercado | menor = melhor (inverter sinal) |
| Valor | patrimônio líquido ÷ valor de mercado | maior = melhor |
| Rentabilidade | lucro bruto ÷ ativo total | maior = melhor |
| Investimento | (ativo_t − ativo_t−1) ÷ ativo_t−1 | menor = melhor (inverter sinal) |

*Nota de robustez de dado:* a fórmula de rentabilidade "textbook" (receita − custos − SG&A − juros) sofre com campos incompletos nas fontes gratuitas. Lucro bruto ÷ ativo total (Novy-Marx) é a versão defensável e obtível.

**Fase 4 — Padronização (winsorize + z-score).** Antes de comparar, cortam-se os extremos de cada fator (percentil 1 e 99) — dado contábil tem erro e outlier que distorce a média. Depois, para cada fator, calcula-se média e desvio-padrão **entre todas as empresas na mesma data** (comparação cross-sectional, nunca a empresa contra o próprio passado) e converte-se cada valor em z-score. Isso põe os 4 fatores na mesma escala e permite somá-los.

**Fase 5 — Nota composta.** Média simples dos 4 z-scores = 1 número por empresa.

**Fase 6 — Seleção.** Ranqueia pela nota, seleciona o top ~50 (ou top 10% do universo), peso igual. Peso igual é decisão deliberada: otimizar peso em cima de histórico curto introduz mais viés do que resolve.

**Fase 7 — Regra de defasagem (look-ahead bias).** Um balanço só "existe" para o modelo ~3 meses depois do fechamento fiscal **daquela empresa específica** (nem toda empresa fecha em dezembro — Apple fecha em setembro, Walmart em janeiro). Sem isso, o backtest usa informação indisponível na data real.

**Fase 8 — Rebalanceio.** Anual (bate com o ciclo de divulgação de balanço). Em cada data, repetem-se as Fases 3-6.

### 1.4. Exemplo numérico (mecanismo em 5 empresas fictícias)

Dados brutos (US$ bi): A(mc50,eq20,gp8,at40/42), B(500,100,60,300/250), C(10,8,3,12/11), D(200,150,40,180/170), E(80,10,15,60/65).

Ranking resultante (nota composta): **C (0,63) > E (0,37) > D (0,14) > A (0,07) > B (−1,22)**.

Sanidade: B é a maior, mais cara, menos rentável e a mais agressiva em crescimento de ativo — corretamente em último. C é pequena, barata, rentável e conservadora — em primeiro. Quando o exemplo confirma a história que a estratégia conta, a lógica está implementada certa.

### 1.5. Testes e validação

- **Backtest:** retorno mensal da carteira (peso igual = média simples dos retornos das ações selecionadas), encadeado período a período, buy-and-hold entre rebalanceios. *Nota:* rebalanceio anual não significa retorno anual — usa-se retorno mensal para que volatilidade e Sharpe tenham significância estatística.
- **Benchmark:** S&P 500 (SPY), mesmo período exato.
- **Métricas:** CAGR, volatilidade (desvio-padrão mensal anualizado por √12), Sharpe (excesso sobre RF ÷ vol), Max Drawdown (maior queda pico-a-vale).
- **Regressão de validação:** retorno em excesso da carteira ~ Mkt-RF + SMB + HML + RMW + CMA + Momentum. Espera-se loadings positivos em SMB/HML/RMW/CMA (prova de que a carteira carrega os fatores prometidos); o intercepto é o alpha. Reportar p-valores — com ~50-70 observações mensais e 6 variáveis, é esperado que nem tudo saia estatisticamente "limpo"; declarar, não esconder.

### 1.6. Tratamento de casos-limite

Empresa sem qualquer um dos 4 dados numa data de rebalanceio (IPO recente, dado furado) sai do ranking **daquele ano** — sem estimar nem preencher com média setorial. Reduzir o universo elegível é mais honesto do que inventar dado.

---

## 2. Sleeve 2 — Small Caps (regime + momentum/reversão)

### 2.1. Fundamentação teórica

Hipótese afiada (mais forte do que "correlacionar com tudo"): small caps dos EUA são desproporcionalmente sensíveis a **crédito e juros domésticos**, por três características estruturais:
1. Receita mais concentrada nos EUA (menos multinacionais) → mais sensíveis à macro doméstica do que à global.
2. Maior dependência de crédito bancário e dívida a taxa flutuante → mais sensíveis a condições financeiras/spread de crédito.
3. Fração grande de empresas ainda não lucrativas (sobretudo no Russell 2000) → mais frágeis a aperto de financiamento.

A estratégia tem **duas camadas**: uma decide *quanto* alocar em small caps (regime macro); a outra decide *quais* small caps comprar (momentum + reversão).

### 2.2. Processo de decisão — os 5 pontos em aberto e como resolvê-los

Estes pontos formam uma cadeia de dependência, não decisões soltas. O princípio transversal: **calibrar contra referência externa (crises documentadas, literatura, características do universo) — nunca contra o retorno do próprio backtest**, o que seria a "escolha oportunista de período" penalizada pelo edital.

**Ponto 1 — Universo.** Candidatos: Russell 2000 (IWM), CRSP US Small Cap (VB) e S&P 600 (IJR). O S&P 600 tem filtro de lucratividade — remove justamente as empresas mais sensíveis ao fenômeno da tese, enfraquecendo o sinal de regime. O CRSP é o "meio-termo": sem filtro de lucratividade (mantém as arriscadas, como o Russell), mas com zonas de amortecimento na reconstituição (reduz o ruído do "efeito de reconstituição Russell"). *Como decidir de fato:* correlacionar cada proxy (IWM/VB/IJR) com o spread de crédito durante crises reconhecidas (2015-16, 2020, 2022-23); o que mostrar relação mais forte e limpa é o universo certo. Dado de composição: via holdings públicos do ETF (mesma ressalva de viés de sobrevivência).

**Ponto 2 — Limiares do gatilho.** Sinal: spread entre o rendimento corporativo Baa da Moody's e o Treasury de 10 anos (FRED, `BAA10Y`), como z-score contra média móvel de 3 anos. A substituição preserva um indicador de estresse de crédito e fornece histórico oficial desde 1986. Calibração: marcar visualmente onde ficam 2008, 2011, 2015-16, 2020 e 2022-23 na série de z-score; o limiar de **entrada** é o valor que capturaria a maioria dessas crises sem disparar demais em período normal; o limiar de **saída** (mais folgado — histerese) calibra-se pelo tempo típico de normalização das crises. Ponto de partida convencional: entrada em z > 1,0, saída em z < 0,5.

**Ponto 3 — Binário ou gradual.** Decidir olhando um gráfico de dispersão: z-score do spread (X) vs. retorno relativo futuro das small caps (Y). Se houver "quebra" clara → binário reflete a realidade e é mais fácil de defender. Se for gradiente contínuo → ajuste gradual captura mais informação, ao custo de mais uma regra. *Recomendação atual:* binário, pela simplicidade defensável no prazo disponível.

**Ponto 4 — Frequência.** Tensão real: reversão de curtíssimo prazo (1 semana) se resolve antes de um rebalanceio mensal. Solução adotada: **redefinir a reversão para horizonte de 1 mês** e rebalancear todo o Sleeve 2 mensalmente — cadência única, compatível com o momentum.

**Ponto 5 — Tamanho da carteira.** Definir como **% do universo** (ex.: top 5%), não número fixo — senão o "tamanho certo" muda conforme o Ponto 1. Peso igual entre os selecionados. Combinação momentum/reversão: 50/50 como ponto de partida; se houver tempo, testar univariado (só momentum, só reversão, composto) contra retorno futuro.

**Mapa de dependência:** Ponto 1 → afeta 3 (quão limpo o regime) → afeta 5 (tamanho como % do universo). Os sinais da Camada 2 → definem 4 → podem forçar redefinição de um sinal (caso da reversão).

### 2.3. Construção quantitativa

**Camada 1 — sinal de regime.** Z-score do spread de crédito mês a mês (referência: média móvel de 3 anos) + regra de histerese (entra em modo defensivo acima do limiar de entrada; só volta abaixo do limiar de saída). Saída: série temporal mensal de "normal" / "estresse".

**Camada 2 — momentum + reversão.** Para cada ação, em cada mês: z-score do momentum (retorno de 12 meses, excluindo o mês mais recente — o "skip" de 1 mês evita o efeito de reversão de curtíssimo prazo) e z-score da reversão (retorno do último mês, sinal invertido — "perdedor recente" é o que interessa). Composto = média dos dois. Ranqueia, seleciona top X% (Ponto 5), peso igual. *Mesma técnica de padronização do Sleeve 1 — coerência deliberada.*

**Combinação das camadas (binária).** Mês a mês: se regime "normal", o peso reservado a small caps vai para a carteira da Camada 2; se "estresse", esse peso migra inteiro para renda fixa e a Camada 2 nem é consultada.

### 2.4. Testes e validação

- **Backtest em duas versões lado a lado:** (a) completa, com Camada 1 ativa; (b) "sempre ligada", só Camada 2, sem filtro de regime. A diferença entre as duas é a prova concreta de que o sinal de regime agrega valor — não é regra decorativa.
- **Benchmark:** o índice/ETF escolhido no Ponto 1.
- **Métricas:** CAGR, vol, Sharpe, Max Drawdown das duas versões e do benchmark.
- **Regressão:** retorno da versão final ~ FF5 + momentum. SMB deve sair claramente positivo (confirma que é carteira de small caps); alpha mede o que sobra.

### 2.5. Limitações a declarar

- Limiares calibrados em amostra pequena de crises — poucas observações para validar um regime estatisticamente.
- Composição via ETF atual (viés de sobrevivência).
- Regra binária simplifica relação possivelmente gradual (escolha deliberada).
- Empilhar regime + momentum + reversão = 3 fontes de sinal → risco de overfitting, só parcialmente mitigado pela comparação "com regime vs. sem regime".

---

## 3. Sleeve 3 — Renda Fixa (âncora + refúgio)

### 3.1. Papel e princípio de design

É deliberadamente o sleeve mais simples. Um âncora que precisa de estratégia própria deixa de ser âncora. Não tem hipótese própria, backtest isolado nem otimização — investir tempo de pesquisa aqui tira tempo de onde o edital realmente pontua (Conceito e Modelagem valem 20% cada nos outros sleeves).

### 3.2. Instrumento

**BIL** (T-bill 1-3 meses), **não SHY** (1-3 anos). Motivo: o gatilho de crédito frequentemente coincide com aperto de juros (2022-23). Um título de prazo mais longo (SHY) pode perder valor por risco de juros **ao mesmo tempo** que o crédito aperta — anulando a função de refúgio na hora que mais importa. BIL tem risco de duração perto de zero: acompanha a política do Fed, não sofre com a alta de juros.

### 3.3. Dinâmica (a única "estratégia" do sleeve)

Duas funções, um instrumento só (o que muda é o peso):
1. Fatia permanente do 33/33/33.
2. Refúgio tático: recebe o capital que sai do Sleeve 2 no estresse.

| Estado (sinal do Sleeve 2) | Factor | Small Caps | Renda Fixa |
|---|---|---|---|
| Normal | 33% | 33% | 33% |
| Estresse | 33% | 0% | 67% |

Factor Investing nunca muda (sem gatilho próprio). Small Caps e Renda Fixa são espelho: migração sempre em bloco, binária.

### 3.4. Cadência e cálculo

- Frequência: mensal, sincronizada com a checagem do sinal de regime do Sleeve 2 — sem rebalanceio próprio, apenas reativo.
- Retorno do mês: peso × retorno **total** do BIL (preço + juros; usar preço ajustado, senão perde-se o carrego, que é a maior parte do retorno de um T-bill).

### 3.5. Validação

Sem regressão própria. O efeito aparece na regressão do fundo consolidado: o beta de mercado do fundo todo sai mais baixo do que o de qualquer sleeve de ação isolado — prova visual de que a âncora cumpre a função.

---

## 4. Consolidação do fundo e avaliação integrada

### 4.1. Montagem do portfólio consolidado

Em cada mês: (1) checar o sinal de regime; (2) definir pesos (33/33/33 ou 33/0/67); (3) compor o retorno do mês = soma ponderada dos retornos dos três sleeves. Encadear ao longo do histórico comum aos três → curva de capital única do fundo.

### 4.2. Régua de avaliação final

- **Métricas do fundo consolidado** vs. um benchmark combinado coerente (ex.: 2/3 índice de ações + 1/3 T-bill) e vs. cada sleeve isolado — mostra o ganho de diversificação.
- **Regressão FF5 + momentum do fundo consolidado:** o alpha do conjunto e o beta de mercado reduzido (efeito da renda fixa) são os dois números-chave da tese.
- **Correlação entre os sleeves:** matriz de correlação dos retornos dos três — quanto menor a correlação entre Factor e Small Caps, mais forte o argumento de diversificação. Este é, na prática, o teste que confirma ou refuta a tese central do fundo.

### 4.3. Sequência de execução recomendada

1. Fechar as decisões em aberto do Sleeve 2 (Ponto 1 primeiro — desbloqueia os demais).
2. Construir e testar cada sleeve isoladamente (Sleeve 1 e 2 em paralelo; Sleeve 3 é trivial).
3. Consolidar e rodar a régua integrada (4.2).
4. Só então traduzir para o relatório de 5 páginas.

---

## 5. Riscos metodológicos transversais (checklist honesto)

| Risco | Onde aparece | Mitigação adotada |
|---|---|---|
| Viés de sobrevivência | Universo via composição atual (Sleeves 1 e 2) | Declarar explicitamente; efeito conhecido (infla retorno) |
| Look-ahead bias | Dados fundamentalistas (Sleeve 1) | Defasagem de ~3 meses por empresa |
| Overfitting | Empilhamento de sinais (Sleeve 2) | Comparação com/sem regime; calibração externa, não no backtest |
| Escolha oportunista de período | Limiares e janelas (Sleeve 2) | Calibrar contra crises documentadas |
| Significância estatística fraca | Histórico curto (todos) | Reportar p-valores; declarar limitação |
| Dado incompleto | Fontes gratuitas (Sleeves 1 e 2) | Excluir empresa do ranking, não imputar |

---

## 6. Ponte para a entrega do challenge (etapa posterior)

Quando chegar a hora do relatório de 5 páginas (PDF, 16:9, ~750 palavras, anônimo, sem apresentação oral): o conteúdo denso deste documento **não** vai para o papel. Ele vira, por página:

- **P1:** robô + tese central + diagrama dos 3 sleeves.
- **P2:** Sleeve 1 — tabela dos 4 fatores + curva de capital vs. S&P 500.
- **P3:** Sleeve 2 — diagrama das 2 camadas + curva com/sem regime vs. benchmark.
- **P4:** fundo consolidado — curva única + tabela de métricas + resultado da regressão + matriz de correlação.
- **P5:** uso de GenAI (15% da nota — peso de Backtest inteiro) + conclusão, limitações e próximos passos.

Todo o detalhamento (fórmulas, winsorize, código, calibração) é munição para a defesa oral das fases seguintes (Quartas/Semifinal têm Q&A), não para o PDF.

**Recomendação operacional imediata:** manter, desde já, um log de uso de GenAI (ferramenta, propósito, o que entrou, onde impactou) — reconstruir de memória na última semana é a forma mais fácil de perder os 15% desse critério.
