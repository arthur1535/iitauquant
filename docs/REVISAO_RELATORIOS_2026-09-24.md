# Revisão dos relatórios de ações — 24/09/2026

Esta revisão cobre os cinco relatórios HTML de MUTC34 (Micron), P2LT34 (Palantir), TSMC34, ASML34 e CATP34. O objetivo foi corrigir fatos que podiam induzir uma decisão de compra, separar evidência de hipótese e deixar os geradores reproduzíveis com os dados locais.

## Mudanças principais

- **MUTC34:** o relatório agora distingue exposição média do sinal (33,0% das sessões) de capital permanentemente investido; calcula a paridade 6:1 a partir do programa consultado na CVM; trata o 10-Q como não auditado; corrige a leitura de 16 acordos de HBM; apresenta P/VP como aproximação; explicita custos, execução t+1, gaps, caixa sem remuneração e a convenção de Sharpe; remove promessas de hedge, imunidade, preservação de capital e venda automática pelo stop.
- **P2LT34:** o gerador continua offline e reconcilia receita, margem bruta, margem operacional, caixa e arrendamentos a partir do release/10-Q; remove linguagem de monopólio, garantia de contratos, risco zero e entrada perfeita; mantém o alerta de que o gráfico e o momentum são snapshots históricos.
- **TSMC34:** o cabeçalho identifica o snapshot de 21/09 e a revisão de 24/09; a análise não afirma participações de mercado de 90%/100%, corrige a hipótese de EPS e trata risco de Taiwan, capex e múltiplo como condicionais.
- **ASML34:** a guidance de €43–45 bi é comparada à receita de 2025 para mostrar o crescimento implícito de aproximadamente 32%–38%; foram retiradas ordens, capacidade vendida, percentuais de China e auditoria trimestral sem fonte suficiente; EPS FY2025, margem 2T25 e evento de mercado foram corrigidos; múltiplos de provedor e cenários estão marcados como secundários ou não calibrados.
- **CATP34:** o relatório marca cotações e múltiplos como snapshot histórico, identifica consenso e preço-alvo como estimativas secundárias, deixa a paridade 1/16 sujeita à confirmação no programa vigente e mantém o nome em watchlist preliminar.

## Fontes e limites

Foram priorizados releases e relações com investidores das companhias, SEC EDGAR e o registro CVM do BDR quando a afirmação exigia fonte primária. Estimativas de mercado, preços históricos e datas futuras continuam identificadas como secundárias, aproximadas ou a confirmar. A revisão não baixa cotações em tempo real, não executa ordens e não transforma cenários em recomendação personalizada.

Os gráficos de Micron foram regenerados a partir de data/market e dos resultados locais. Distâncias de ATR nos gráficos são referências de risco; não são stops cumulativos garantidos. O backtest permanece exploratório/pseudo-OOS e não substitui validação fora da amostra.

## Validação executada

- python -m py_compile nos três scripts de geração/revisão;
- geração offline de MUTC34, P2LT34 e dos três gráficos de Micron;
- git diff --check;
- inspeção textual dos cinco HTMLs para eliminar alegações de garantia, auditoria trimestral, cotação em tempo real e consenso apresentado como fato;
- suíte histórica do repositório preservada: 139 testes Python e 37 testes Node aprovados no checkpoint de 21/09/2026. A revisão de relatórios não altera a lógica do motor de ordens paper-only.

Nenhuma decisão de investimento deve ser tomada apenas com estes arquivos. É necessária revisão humana, atualização dos dados e confirmação da paridade/liquidez antes de qualquer operação.
