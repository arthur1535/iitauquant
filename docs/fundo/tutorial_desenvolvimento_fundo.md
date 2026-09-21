# Tutorial de Desenvolvimento — Fundo Multi-Sleeve (passo a passo, do zero ao fim)
### Documento-guia da equipe · Desafio Quant AI 2026

> **Como usar este documento:** siga na ordem. Cada passo diz **o que fazer**, **como fazer**, **como saber se deu certo** e **o que costuma dar errado**. Os passos com 🔴 são pontos onde uma decisão precisa ser tomada e registrada antes de continuar. Não pule etapas — a ordem existe porque cada passo desbloqueia o seguinte.

---

## ETAPA 0 — Preparação (meio dia)

### Passo 0.1 — Montar o ambiente de trabalho
**O que fazer:** deixar o computador pronto para trabalhar com dados.
**Como:** instalar Python (ou usar o Google Colab, que não exige instalar nada e roda no navegador — recomendado se ninguém do grupo tem ambiente configurado). Instalar as bibliotecas: `yfinance`, `pandas`, `numpy`, `statsmodels`, `matplotlib`.
**Como saber se deu certo:** conseguir importar as 5 bibliotecas sem erro.
**Erro comum:** perder um dia inteiro configurando ambiente local. Se travar por mais de 1 hora, migre pro Colab e siga em frente.

### Passo 0.2 — Criar a estrutura de pastas do projeto
**O que fazer:** uma pasta por sleeve + uma pasta `dados/` + uma pasta `resultados/`. Dentro de `dados/`, uma subpasta `cache/` (os fundamentos baixados empresa a empresa vão aqui, para nunca precisar baixar duas vezes).
**Por quê:** o download de fundamentos é lento e falha no meio — sem cache, cada falha significa recomeçar do zero.

### Passo 0.3 — Abrir o log de GenAI (hoje, não depois)
**O que fazer:** uma planilha simples com 4 colunas: data · ferramenta usada · o que foi pedido · onde o resultado entrou no projeto.
**Por quê:** esse critério vale 15% da nota — o mesmo peso do Backtest inteiro. Preencher em tempo real custa 1 minuto por uso; reconstruir de memória na última semana custa pontos.
**Primeira linha do log:** este próprio processo de planejamento com IA já é um uso registrável.

---

## ETAPA 1 — Análise exploratória que destrava as decisões (2-3 dias)

Esta etapa vem ANTES de construir qualquer carteira. Ela existe para transformar os parâmetros "em aberto" em números fechados — usando dado real, não achismo.

### Passo 1.1 — Baixar as 4 séries de referência
**O que fazer:** baixar o preço mensal histórico (10+ anos) de: IWM (proxy do Russell 2000), VB (proxy do CRSP Small Cap), IJR (proxy do S&P 600) e SPY (S&P 500, como referência de mercado). Baixar também a série diária do spread corporativo Baa contra o Treasury de 10 anos no FRED (série `BAA10Y`) e converter para mensal pelo último valor observado de cada mês.
**Como saber se deu certo:** 5 séries, todas cobrindo pelo menos 2012-hoje, sem buracos grandes.

### Passo 1.2 — 🔴 DECISÃO: escolher o universo de small caps
**O que fazer:** calcular o retorno mensal de IWM, VB e IJR. Calcular o retorno *relativo* de cada um contra o SPY (retorno do ETF menos retorno do SPY, mês a mês). Plotar cada série relativa contra o spread de crédito, marcando visualmente as janelas de crise: 2015-16, 2020, 2022-23.
**Como decidir:** o ETF cujo retorno relativo cai de forma mais clara e consistente quando o spread sobe é o universo certo — é onde a hipótese da Carteira 2 é mais forte.
**Como saber se deu certo:** vocês conseguem apontar no gráfico "aqui o spread subiu, aqui a small cap apanhou" nas 3 janelas de crise. Se nenhum dos três mostrar esse padrão com clareza, parem e reavaliem a hipótese antes de seguir (é melhor descobrir isso agora).
**Registrar:** qual ETF venceu e por quê (1 parágrafo). Isso vira munição de defesa oral.

### Passo 1.3 — 🔴 DECISÃO: fixar os limiares do gatilho de regime
**O que fazer:** calcular o z-score do spread de crédito contra a média móvel de 3 anos (36 meses). Plotar a série do z-score inteira e marcar as mesmas crises.
**Como decidir:** o limiar de **entrada** é o valor de z que teria capturado a maioria das crises marcadas sem disparar em períodos calmos (ponto de partida: 1,0 — confira se ele captura 2015-16, 2020 e 2022-23 no gráfico; ajuste se necessário, mas só com base no gráfico, nunca no retorno do backtest). O limiar de **saída** deve ser mais folgado (ponto de partida: 0,5) — confira no gráfico se com ele o modelo sai do modo defensivo só quando a crise de fato normalizou, não no primeiro alívio.
**Erro comum (grave):** testar vários limiares, rodar o backtest com cada um e escolher o que dá mais retorno. Isso é a "escolha oportunista" que o edital penaliza — e a banca sabe reconhecer. O limiar se escolhe olhando o gráfico do sinal contra crises conhecidas, ANTES de rodar qualquer backtest.

### Passo 1.4 — 🔴 DECISÃO: binário ou gradual
**O que fazer:** gráfico de dispersão — z-score do spread num mês (eixo X) vs. retorno relativo da small cap escolhida no mês seguinte (eixo Y).
**Como decidir:** se o padrão mostra uma "quebra" (small caps vão bem até certo nível de z, depois desabam) → regra binária, que é o que já está desenhado. Se mostrar um declínio contínuo e proporcional → anotar isso como limitação/próximo passo, mas manter o binário mesmo assim pelo prazo (a decisão consciente + a limitação declarada valem mais que a complexidade extra).

### Passo 1.5 — Teste de viabilidade do dado fundamentalista (Sleeve 1)
**O que fazer:** escolher 15-20 tickers variados do S&P 500 (misture gigantes, médias, setores diferentes) e verificar, um a um, se o provedor gratuito devolve completos: patrimônio líquido, ativo total (2 anos), receita, lucro bruto.
**Como saber se deu certo:** se ≥80% das empresas da amostra têm todos os campos → sigam com o S&P 500 inteiro. Se estiver furado demais → reduzam o universo para o S&P 100 agora, antes de investir em código para 500.
**Por quê agora:** esse é o maior risco de execução do projeto inteiro. Meia hora de teste aqui evita descobrir o problema na semana 3.

**✅ Checkpoint da Etapa 1:** universo da Carteira 2 escolhido · limiares fixados e justificados · binário confirmado · viabilidade do dado do Sleeve 1 confirmada (ou universo reduzido). Só avance com os quatro fechados.

---

## ETAPA 2 — Construir o Sleeve 1: Factor Investing (4-6 dias)

### Passo 2.1 — Obter a lista do universo
**O que fazer:** baixar a lista de tickers do S&P 500 (a tabela pública da Wikipédia serve) e salvar num arquivo. Atenção: tickers com ponto (BRK.B) costumam precisar virar hífen (BRK-B) no provedor de preços.

### Passo 2.2 — Baixar os preços
**O que fazer:** preço mensal ajustado de todos os tickers, de uma vez (o download de preços aceita lote), do máximo de histórico disponível.
**Como saber se deu certo:** uma tabela com datas nas linhas e ~500 colunas; colunas com muitos buracos são empresas com IPO recente — normal.

### Passo 2.3 — Baixar os fundamentos (a parte lenta)
**O que fazer:** loop empresa por empresa, salvando cada resultado no cache imediatamente, com pausa a cada ~20 empresas. Rodem primeiro nos 20 tickers do Passo 1.5 (que já sabem que funcionam), depois soltem nos 500.
**Quanto tempo leva:** conte algumas horas, possivelmente com interrupções. Por isso o cache: cada rodada só busca o que ainda não tem.
**Como saber se deu certo:** ao final, contar quantas empresas têm os 4 fatores calculáveis. Esperem perder 10-20% do universo por dado incompleto — está dentro do normal e essas empresas simplesmente ficam de fora naquele ano (nunca preencham com estimativa).

### Passo 2.4 — Calcular os 4 fatores brutos
**O que fazer (por empresa):**
- Tamanho = valor de mercado (multiplicar por −1: menor é melhor)
- Valor = patrimônio ÷ valor de mercado
- Rentabilidade = lucro bruto ÷ ativo total
- Investimento = crescimento do ativo total ano-a-ano (multiplicar por −1: menor é melhor)
**Como saber se deu certo:** teste de sanidade manual — peguem 3 empresas que vocês conhecem e confiram se os números fazem sentido (uma big tech deve ter fator-tamanho péssimo; um banco tradicional barato deve ter fator-valor bom). Se a intuição bater, a conta está certa.

### Passo 2.5 — Padronizar (winsorize + z-score)
**O que fazer:** para cada fator, cortar os extremos (1% de cada ponta) e converter em z-score comparando as empresas ENTRE SI na mesma data.
**Como saber se deu certo:** nenhum z-score deve passar de ~±5 depois do winsorize. Se aparecer um z de 20, o corte de extremos não funcionou.

### Passo 2.6 — Nota composta e seleção
**O que fazer:** média dos 4 z-scores → ranquear → top ~50 → peso igual.
**Teste de sanidade obrigatório:** olhem a lista das 50 escolhidas. Deve ter cara de "empresas menores do índice, baratas, rentáveis, discretas" — não as queridinhas de crescimento do momento. Se a lista parecer um top-50 de empresas da moda, algum sinal está invertido (provavelmente esqueceram um dos "multiplicar por −1").

### Passo 2.7 — Aplicar a defasagem e montar as carteiras históricas
**O que fazer:** para cada ano do backtest, repetir os passos 2.4-2.6 usando o balanço daquele ano — respeitando a regra: o balanço só "existe" ~3 meses após o fechamento fiscal daquela empresa específica.
**Limitação prática a aceitar:** com fonte gratuita (~4 anos de balanço), vocês terão ~4 carteiras anuais. É suficiente para o desafio; registrem como limitação.

### Passo 2.8 — Backtest
**O que fazer:** entre cada rebalanceio, o retorno mensal da carteira = média simples do retorno das 50 ações. Encadear tudo → curva de capital. Fazer a mesma curva para o SPY, mesmo período exato.
**Como saber se deu certo:** nenhum retorno mensal da carteira deve passar de ±30% (S&P 500 diversificado não faz isso) — se aparecer, há erro de alinhamento de datas ou preço não ajustado.

### Passo 2.9 — Métricas + regressão de validação
**O que fazer:** CAGR, volatilidade anualizada, Sharpe, Max Drawdown — carteira vs. SPY. Depois, baixar os fatores mensais FF5 + Momentum do site do Kenneth French e rodar a regressão (retorno da carteira menos RF, explicado pelos 6 fatores).
**Como saber se deu certo:** loadings positivos em SMB, HML, RMW e CMA. Esse é O teste do sleeve inteiro: confirma que a carteira entrega os fatores que promete. Se algum vier negativo, voltem ao passo 2.4 e procurem sinal invertido.
**Registrar:** alpha (com p-valor — provavelmente não significativo com histórico curto, e tudo bem: declara-se) e os 4 loadings.

**✅ Checkpoint da Etapa 2:** curva de capital vs. SPY plotada · tabela de métricas · regressão com loadings positivos nos 4 fatores.

---

## ETAPA 3 — Construir o Sleeve 2: Small Caps (4-6 dias, pode ser em paralelo com a Etapa 2 se dividirem o time)

### Passo 3.1 — Obter o universo
**O que fazer:** baixar o arquivo de holdings do ETF escolhido no Passo 1.2 (site do gestor do fundo, arquivo público). Extrair a lista de tickers.
**Escolha prática:** se o universo tiver 1000+ nomes (Russell/CRSP), trabalhem com um recorte líquido (ex.: os 500 maiores dentro do índice) — o custo de dado cai muito e a tese não muda.

### Passo 3.2 — Baixar os preços
Igual ao Passo 2.2, para o universo de small caps. Aqui NÃO precisa de fundamento nenhum — o Sleeve 2 é 100% preço, o que o torna muito mais rápido de construir que o Sleeve 1.

### Passo 3.3 — Construir a Camada 1 (o sinal de regime)
**O que fazer:** com o z-score do spread (Passo 1.3) e os limiares fixados, gerar a série mensal de estados: "normal" ou "estresse", com a regra de memória (histerese): entra em estresse quando z cruza o limiar de entrada; SÓ volta ao normal quando z cai abaixo do limiar de saída.
**Como saber se deu certo:** plotar a série de estados sobre o gráfico do spread. Os blocos de "estresse" devem coincidir com as crises conhecidas e durar vários meses seguidos — se o estado ficar piscando (troca todo mês), a histerese não está funcionando.

### Passo 3.4 — Construir a Camada 2 (momentum + reversão)
**O que fazer (por ação, em cada mês):**
- Momentum = retorno dos 12 meses TERMINANDO no mês passado (pula o mês mais recente)
- Reversão = retorno do mês mais recente, com sinal invertido
- Z-score de cada um (entre as ações, na mesma data) → média dos dois = nota composta → top 5% do universo → peso igual
**Teste de sanidade:** peguem um mês qualquer e olhem as 5 primeiras do ranking. Deve haver mistura de "ações em tendência de alta no ano" e "ações que apanharam no último mês" — se só houver um dos perfis, um dos z-scores está dominando (confiram a padronização).

### Passo 3.5 — Backtest em DUAS versões (obrigatório)
**O que fazer:** rodar mês a mês:
- **Versão A ("sempre ligada"):** todo mês, 100% na seleção da Camada 2, ignorando o regime.
- **Versão B ("com regime"):** meses normais = Camada 2; meses de estresse = retorno do BIL.
**Por quê duas:** a diferença entre as curvas é a prova visual de que o sinal de regime agrega valor. É o gráfico mais persuasivo do projeto inteiro.
**Como saber se deu certo:** nos meses de estresse, o retorno da Versão B deve ser EXATAMENTE o retorno do BIL (confiram alguns meses no olho). A Versão B deve mostrar quedas mais rasas que a A justamente nas janelas de crise.

### Passo 3.6 — Métricas + regressão
Igual ao Passo 2.9, para as duas versões + o ETF do universo como benchmark. Na regressão, o loading de SMB deve sair claramente positivo (confirma que é de fato uma carteira de small caps).

**✅ Checkpoint da Etapa 3:** série de regime plotada e coerente com crises · duas curvas de backtest · Max Drawdown da versão com regime menor que o da sempre-ligada · SMB positivo na regressão.

---

## ETAPA 4 — Sleeve 3 e consolidação do fundo (2-3 dias)

### Passo 4.1 — Sleeve 3 (rápido de propósito)
**O que fazer:** baixar o preço mensal AJUSTADO do BIL (sem o ajuste, perde-se o carrego — que é quase todo o retorno de um T-bill) e calcular o retorno mensal. Pronto: o Sleeve 3 não tem mais nada.

### Passo 4.2 — Montar o fundo consolidado
**O que fazer (mês a mês, no período comum aos três sleeves):**
1. Consultar o estado do regime (Passo 3.3).
2. Definir pesos: normal → 33/33/33; estresse → 33 (Factor) / 0 (Small Caps) / 67 (Renda Fixa).
3. Retorno do fundo no mês = soma ponderada dos retornos dos três sleeves.
4. Encadear → curva de capital única do fundo.
**Atenção ao período comum:** o Sleeve 1 provavelmente terá o histórico mais curto (limite do dado fundamentalista) — o fundo consolidado fica limitado a esse período. Os backtests individuais mais longos continuam valendo como análise de cada sleeve.

### Passo 4.3 — A régua integrada (a análise que fecha a tese)
**O que fazer:**
1. **Métricas do fundo** vs. benchmark combinado (2/3 índice de ações + 1/3 BIL) e vs. cada sleeve isolado.
2. **Matriz de correlação** dos retornos mensais dos três sleeves. Este é o teste da tese central: correlação baixa entre Factor e Small Caps = a diversificação prometida existe. Se vier alta (>0,8), a tese de "dois motores diferentes" enfraquece — e isso se reporta com honestidade, não se esconde.
3. **Regressão FF5+Momentum do fundo consolidado:** o beta de mercado do fundo deve sair visivelmente menor que o dos sleeves de ação isolados (efeito da âncora de renda fixa) — é a prova de que o Sleeve 3 cumpre a função.

**✅ Checkpoint da Etapa 4:** curva única do fundo · matriz de correlação · beta do fundo < beta dos sleeves de ação.

---

## ETAPA 5 — Análise crítica e fechamento (1-2 dias)

### Passo 5.1 — Escrever a lista de limitações (sem cosmética)
Já mapeadas ao longo do caminho — consolidar: viés de sobrevivência (universos atuais) · look-ahead mitigado mas não eliminado · histórico curto → alpha sem significância estatística · limiares calibrados em poucas crises · regra binária simplifica relação possivelmente gradual · risco de overfitting por empilhamento de sinais (parcialmente respondido pelo backtest em duas versões).

### Passo 5.2 — Escrever os próximos passos (realistas, não grandiosos)
Exposição gradual em vez de binária · validar o peso 50/50 momentum/reversão · estender o histórico com base de dados paga · custos de transação.

### Passo 5.3 — Congelar os resultados
**O que fazer:** salvar TODAS as tabelas e gráficos finais em `resultados/`, com data. A partir daqui, nenhum parâmetro muda mais — mudar parâmetro depois de ver o resultado final é exatamente o vício metodológico que todo o processo acima existiu para evitar.

---

## Ordem de ataque e divisão de time (sugestão para 3 pessoas)

| Quem | Frente |
|---|---|
| Pessoa 1 | Etapa 1 (exploratória) → depois Sleeve 2 |
| Pessoa 2 | Sleeve 1 (começa pelo Passo 1.5 + 2.1-2.3, que são os mais lentos) |
| Pessoa 3 | Log de GenAI + Sleeve 3 + consolidação + começa a esboçar o relatório de 5 páginas em paralelo |

Regra de ouro do cronograma: **o download de fundamentos do Sleeve 1 (Passo 2.3) começa o mais cedo possível** — é a tarefa mais lenta e a única que não dá pra acelerar; tudo o mais pode andar em volta dela.

---

## Erros que eliminam projetos (recapitulação final)

1. Escolher parâmetro olhando o retorno do backtest (limiar, janela, peso) — calibração é sempre externa e anterior.
2. Usar dado que não existia na data (balanço sem defasagem, composição atual sem declarar).
3. Preencher dado faltante com estimativa — exclui-se a empresa, não se inventa.
4. Regra "coerente" sem número — toda decisão do modelo precisa ser um número que um script executa sem interpretação.
5. Deixar o log de GenAI pra depois.
