# Revisão do projeto — 09/10/2026

## Entrega

Pesquisa de curto prazo de 24 ações e ETFs dos EUA, em USD, conforme o universo e o horizonte escolhidos pelo usuário. O ponto de entrada é `scripts/run_investment_research.py`; a metodologia está em [INVESTMENT_RESEARCH.md](INVESTMENT_RESEARCH.md).

O relatório em [relatorio.html](../results/investment_research/2026-10-09/relatorio.html) usa o fechamento de 08/10/2026. O pregão de 09/10 estava aberto durante a coleta e foi excluído. Houve 24 séries válidas, nenhuma exclusão e 11 sinais técnicos. PLTR e MU também tiveram retorno e Sharpe positivos no recorte retrospectivo, com pelo menos dez operações e resultado positivo sob custo maior. Isso prioriza diligência; não demonstra alpha, preço justo ou vantagem futura.

Na janela comum de 16/12/2024 a 08/10/2026, a regra de PLTR rendeu 42,1%, contra 164,0% ao comprar e manter PLTR; a de MU rendeu 431,4%, contra 882,9% ao comprar e manter MU. O SPY passivo rendeu 30,3%. As estratégias têm exposição diferente, foram selecionadas entre diversos ativos e não demonstram superioridade geral. Drawdowns OOS das regras de PLTR e MU foram, respectivamente, -33,0% e -26,0%. Os números são históricos líquidos dos custos simulados, antes de impostos e câmbio.

## Mudanças verificáveis

- Novo módulo isolado de coleta, validação, filtros, ranking, simulação causal e relatório. Cache em `data/swing_us/`, com hashes e sidecars; não reutiliza silenciosamente caches antigos.
- Configuração explícita de universo, custos, prazo, liquidez e orçamento de risco. Não há conexão com corretora.
- README reorganizado por fluxo de uso, documentação de método, índices e CI para Python e Cloudflare.
- Empacotamento corrigido para incluir `quant_fund`, além dos módulos em `src/`; CLI `iitauquant-research` registrada.
- Sleeve fundamentalista corrigido para impedir que revisões futuras alterem o crescimento dos ativos usado em sinais passados.
- Adaptador SEC aceita ausência do campo opcional `tag_priority`; calendário mensal rejeita meses inteiramente omitidos e aceita ausência explicitamente declarada como NA.

## Validação

Em 09/10/2026: **180 testes Python aprovados**, três subtestes aprovados e **37 testes Cloudflare aprovados**. Os dois avisos Python são de depreciação de dependências de TestClient/AnyIO. O wheel foi construído sem baixar dependências; imports isolados e entrada da CLI foram verificados fora do checkout. O HTML foi renderizado em Chrome sem janela e inspecionado em layout amplo e estreito.

Os testes novos cobrem revisões futuras de fundamentos, calendário mensal, execução na próxima abertura, custos nas duas pontas, gap stop, atualização causal do stop, prazo máximo, início do teste sem posição herdada, invariância a barras futuras, rejeição de dados defasados/lacunas/cache corrompido, consistência de escala e ATR zero.

## Limites que permanecem

Universo atual escolhido manualmente, avaliação retrospectiva e múltiplas comparações impedem interpretar a classificação como validação prospectiva. Calendário de resultados, notícias materiais, composição de ETFs, spreads reais e tributação não foram incorporados. O sizing é uma referência individual, não uma carteira consolidada. O fundo LASTRO continua sendo uma frente distinta; a nova simulação com custos não modifica automaticamente os retornos históricos desse fundo.

O cache diário anterior continha datas diferentes, ausência de sidecars e fontes de ajuste pouco explícitas. A camada mensal tinha cobertura incompleta de fundamentos SEC e holdings. Essas lacunas não foram preenchidas com dados sintéticos nem promovidas a evidência da nova pesquisa.
