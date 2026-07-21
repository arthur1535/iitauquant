# Checklist — Pré-Relatório (31/07/2026)

**Base:** confirmado = está em algum dos 7 documentos oficiais ou no mecanismo do desafio. Inferido = deduzido da lógica do processo, sem confirmação direta — sinalizado como tal.

---

## Prioridade — o que é inegociável vs. o que pode ir incompleto

| Prioridade | Bloco |
|---|---|
| 🔴 **Obrigatório, sem desculpa** | Tese central + Nome/identidade do robô + Dados e universo definidos |
| 🟡 **Tem que aparecer, mesmo que parcial** | Modelagem dos 3 sleeves + Backtest preliminar (números reais, mesmo que só do Sleeve 1) + Log de GenAI |
| 🟢 **Pode estar em aberto, desde que declarado como tal** | Sleeve 2 completo (os 5 pontos), consolidação final do fundo, regressão FF5 do fundo todo |

O critério que sustenta essa ordem: **[confirmado]** a régua de avaliação em todos os 4 documentos recompensa honestidade e clareza acima de resultado bonito ("um resultado ruim não elimina o trabalho"; "análise crítica" pesa mais que "resultado"). Chegar no pré-relatório dizendo "o Sleeve 2 está com o método definido, decisão pendente" é mais forte do que forçar um número que ainda não é real.

---

## Bloco A — Identidade do robô 🔴

- [ ] Nome do robô definido
- [ ] Identidade visual (mínima — não precisa ser produção gráfica final, mas precisa existir)
- [ ] Explicação de 2-3 frases do porquê do nome

**Como fazer:** o nome precisa remeter à tese (2 motores pouco correlacionados + âncora de refúgio), não a "quant" ou "IA" genérico. Teste: alguém que só vir nome + explicação consegue desconfiar da lógica de 3 pernas? Se não, ajuste.

**Por que entra já no pré-relatório:** *[inferido]* — é a etapa 3 das 6 do desafio (antes de "coleta de dados" e "modelagem"), então na lógica do cronograma oficial já deveria estar fechada a essa altura.

---

## Bloco B — Tese / Conceito da estratégia 🔴

- [ ] Hipótese central escrita em 1 parágrafo: **o que** o fundo captura e **por que** isso gera retorno
- [ ] Os 3 sleeves nomeados com o papel de cada um (fundamentalista / técnico / âncora)
- [ ] A lógica de pesos e o gatilho de migração (33/33/33 → 33/0/67) explicada em uma frase
- [ ] Um diagrama simples (3 caixas + seta do gatilho) — não precisa ser o diagrama final de produção

**Como fazer:** use exatamente a tese que já está escrita na seção 0 do relatório técnico — "combinar dois motores de retorno pouco correlacionados... mais uma âncora de renda fixa que também serve de refúgio tático". Isso já está pronto, só precisa ser reduzido a uma página/slide.

---

## Bloco C — Dados 🔴

- [ ] Universo do Sleeve 1: S&P 500, fonte de preços e fundamentos identificada
- [ ] Universo do Sleeve 2: qual proxy foi escolhido entre IWM/VB/IJR — **e se ainda não foi escolhido, isso precisa estar marcado como decisão em aberto, não omitido**
- [ ] Instrumento do Sleeve 3: BIL, com o motivo (duration baixa vs. SHY)
- [ ] Limitações de dado já identificadas: viés de sobrevivência (universo atual, não histórico), ~4 anos de balanço via fonte gratuita

**Como fazer:** isto já está 100% resolvido no seu material técnico para os Sleeves 1 e 3. O único buraco real é o Ponto 1 do Sleeve 2 (qual proxy). Se não fechar a tempo, declare o método de decisão (correlação com spread de crédito HY nas crises de 2015-16/2020/2022-23) e diga que a escolha final está em andamento — isso ainda conta como dado "orientado por dados", que é literalmente o que o Guia de Primeiros Passos define como requisito mínimo de um modelo quantitativo.

---

## Bloco D — Modelagem por sleeve 🟡

Para cada sleeve, o mínimo é: **dado de entrada → o que o modelo faz → que decisão sai.** Isso é a régua exata do "modelo quantitativo" definida no Guia de Primeiros Passos.

**Sleeve 1 (Factor Investing) — este pode estar 100% pronto:**
- [ ] Os 4 fatores com fórmula e direção (Tamanho, Valor, Rentabilidade, Investimento)
- [ ] Winsorize + z-score cross-sectional + nota composta explicados em 2 linhas
- [ ] Regra de seleção: top ~50 / top 10%, peso igual
- [ ] Regra de defasagem (~3 meses pós-fechamento fiscal da empresa) — é o item que prova rigor contra look-ahead bias

**Sleeve 2 (Small Caps) — apresente o que está fechado, marque o que não está:**
- [ ] Camada 1 (regime): lógica do z-score do spread de crédito + histerese — método explicado mesmo que os limiares finais não estejam calibrados
- [ ] Camada 2 (momentum/reversão): momentum 12-1 + reversão 1 mês, composto 50/50
- [ ] O que falta: universo final, limiares de entrada/saída, binário vs. gradual — liste como pendências nomeadas, não omita

**Sleeve 3 (Renda Fixa) — trivial, não precisa de espaço desproporcional:**
- [ ] BIL, função dupla (fatia permanente + refúgio tático), tabela de pesos por estado (normal/estresse)

---

## Bloco E — Backtest preliminar 🟡

- [ ] Pelo menos **um número real**, não projetado — idealmente do Sleeve 1, que é o mais maduro
- [ ] Benchmark identificado (SPY para Sleeve 1; proxy do Sleeve 2 quando definido; blend para o fundo consolidado)
- [ ] Se o Sleeve 2 e a consolidação não estiverem prontos: diga isso explicitamente, com prazo interno de quando devem estar (ex.: "modelagem completa, backtest em execução, resultado esperado até X")

**Por que isso pesa mais do que parece:** *[inferido]* — um checkpoint de meio de projeto que mostra zero número real sugere ao avaliador que o time está atrasado na fase 5 do cronograma oficial (Modelagem e backtest), que deveria estar em andamento agora. Um número real, mesmo que parcial, é a evidência mais forte de que o projeto está vivo.

---

## Bloco F — Uso de GenAI documentado 🟡

- [ ] Lista corrida do que já foi feito: ferramenta usada, para quê, o que mudou no projeto por causa disso
- [ ] Pelo menos 2-3 exemplos concretos (não "usamos ChatGPT para ajudar" — e sim "o Antigravity gerou o pipeline de cálculo dos 4 fatores, que revisamos e ajustamos em X")

**Como fazer:** comece agora, mesmo que o pré-relatório não peça isso explicitamente — o critério vale 15% na entrega final e reconstruir de memória depois é o erro mais comum e mais evitável.

---

## Bloco G — Limitações e riscos reconhecidos 🟢

- [ ] Pelo menos 3 limitações nomeadas (não genéricas): viés de sobrevivência, look-ahead mitigado por defasagem, amostra pequena de crises para calibrar regime
- [ ] Isso pode ser 3-4 linhas, não precisa de seção própria grande

**Por que incluir mesmo cedo:** *[confirmado]* — em todos os 4 documentos, "análise crítica" e "reconhecimento de limitações" aparecem como diferencial positivo explícito, não como admissão de fraqueza.

---

## Bloco H — Formato e envio

- [ ] **Anonimato:** *[inferido, com base forte]* a regra de anonimato total está descrita apenas nas Diretrizes do **Relatório Final**, e a chave de envio anônima só é liberada **depois** da entrega do pré-relatório. Isso sugere que o pré-relatório provavelmente **não** precisa ser anônimo — identifique a equipe normalmente, a menos que o canal diga o contrário.
- [ ] **Formato de arquivo:** *[não confirmado]* nenhum dos documentos especifica PDF/slides/outro para o pré-relatório. Na ausência de instrução, um PDF curto (mesma lógica visual do relatório final — gráfico/tabela acima de texto) é a aposta mais segura, porque reaproveita o que vocês vão precisar depois de qualquer forma.
- [ ] **Envio:** *[confirmado]* instruções de envio (e-mail, procedimento) saem só pelo canal oficial — isso é literal nos documentos. Confirme lá antes de enviar por qualquer outro meio.

---

## Checklist final — antes de enviar

- [ ] Nome do robô + identidade + explicação presentes
- [ ] Tese central em 1 parágrafo + diagrama dos 3 sleeves
- [ ] Universo e dados de cada sleeve nomeados (mesmo com pendência declarada no Sleeve 2)
- [ ] Lógica de dado→sinal→decisão para os 3 sleeves
- [ ] Ao menos um número de backtest real
- [ ] Limitações nomeadas, não genéricas
- [ ] Log de GenAI iniciado, com exemplos concretos
- [ ] Equipe identificada normalmente (não anônimo, salvo instrução em contrário do canal)
- [ ] Confirmado no canal oficial: formato de arquivo, e-mail/procedimento de envio, e se algo mudou nesta lista
