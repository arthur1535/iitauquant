# Auditoria OOS — Tarefa 1: contrato temporal e manifesto

Data: 2026-09-21. Responsável analítico: ChatGPT / OpenAI Codex.
Implementação no terminal: Antigravity, respeitando seus locks no script e nos testes.
Estado: especificação da primeira entrega; validação econômica ainda não executada por esta auditoria.

## Decisão e limite da evidência

Adotar o corte nominal IS até **2022-12-31** e avaliação desde **2023-01-01** até a última barra local disponível na data de corte. É uma escolha de desenho, não um corte selecionado para melhorar métricas. Não usar dezembro de 2026 como se o ano estivesse completo.

Classificação obrigatória: `retrospective_pseudo_oos`. O período já foi observado: a pesquisa Global Leaders ranqueou estratégias em 2020–2026, e o grid/Optuna brasileiro usou 70% do histórico, incluindo 2023–2024. Repartir esses dados agora não recria um teste cego. Manter `shadow_mode=true`, `aprovado=false` e `promotion_allowed=false`.

Um teste prospectivo começa apenas após o congelamento documentado de dados, regras, universo e protocolo, em barras ainda não observadas. O congelamento desta especificação não apaga as pesquisas anteriores.

## Cobertura observada, sem baixar dados nem executar backtest

| Série | Início | Última barra local | Barras até 2022 / desde 2023 |
|---|---|---|---|
| SPY, NVDA, MSFT e demais globais locais | 2020-01-02 | 2026-09-04 | 756 / 922 por ativo |
| VALE3.SA e demais brasileiros locais | 2020-01-02 | 2026-09-02 | 745 / 917 por ativo |
| BIL diário em `data/market/` | ausente | ausente | indisponível |

BIL existe em fontes mensais distintas; elas não substituem OHLC diário. Não combinar calendários ou moedas dos dois mercados silenciosamente. Brasileiros têm coluna `date`; globais usam `DatetimeIndex`: utilizar o carregador canônico, evitando interpretar `RangeIndex` como datas de 1970.

O manifesto exige dados point-in-time, mas os Parquets não comprovam por si só fonte, vintage, constituintes históricos ou ajustes corporativos. O curador brasileiro usa `auto_adjust=False`, descarta `Adj Close` e altera extremos OHLC. Validade estrutural não certifica retorno total. Essas limitações devem constar da cobertura e impedem aprovação econômica, mesmo quando o planejamento temporal funciona.

## Primeira entrega pequena: somente `--dry-run` para SPY

Antigravity deve acrescentar ao `scripts/run_out_of_sample_audit.py` um caminho de planejamento que leia o Parquet local, valide datas/OHLC, construa partições e grave evidências. Nesse modo, não chamar motor de backtest, grade, Optuna, cálculo de métricas, rede ou OMS.

Comando-alvo **a implementar**, não uma execução já realizada:

```powershell
.\.venv\Scripts\python.exe scripts/run_out_of_sample_audit.py --dry-run --symbols SPY --is-end 2022-12-31 --oos-start 2023-01-01 --as-of 2026-09-21 --train-bars 504 --test-bars 63 --purge-bars 1 --embargo-bars 5 --output-dir results/oos_audit/task1_spy
```

Para o arquivo atual, os cortes nominais resolvem em IS **2020-01-02 a 2022-12-30**, 756 barras, e pseudo-OOS **2023-01-03 a 2026-09-04**, 922 barras. Contagens são anteriores a qualquer remoção de fronteira; registrar também as contagens efetivas. SHA-256 observado de `data/market/SPY.parquet`: `dd4c573d6f9c109d3b0e461d9cd759f3d0c7451a3650ec30f578f2cd9d1047ed`.

Desenho escolhido para esta etapa:

1. **Validação interna ao IS:** planejar walk-forward expansivo exclusivamente até 2022, com treino inicial de 504 barras e teste de 63; identificar o último fold incompleto. A grade e sua seleção futura só poderão usar esse IS.
2. **Reserva de avaliação:** separar 2023–última barra, destinada a parâmetros congelados até 2022. Não usar essa reserva para escolher janelas, limiares ou ativos.
3. **Purging e embargo:** 1/5 barras são convenções provisórias para testar a estrutura do planejador, não comprimentos econometricamente aprovados. Declarar `purging_status=gap_only_not_event_purged`. O splitter atual usa gaps fixos e não recebe intervalos de labels/trades. A suficiência do purge depende do horizonte informacional efetivo; ATR=14 não implica purge=14. Antes da etapa de métricas, documentar os intervalos de eventos ou justificar uma política de fronteiras que impeça sobreposição. A reserva OOS não pode ser deslocada silenciosamente.
4. **Semântica do embargo existente:** ele pula barras entre testes internos; não equivale automaticamente ao embargo por eventos do CPCV. Barras omitidas devem ser identificadas no manifesto.
5. **Aquecimento e posições:** histórico passado pode aquecer indicadores sem contabilizar P&L fora do intervalo. Preservar execução em t+1. O motor inicia cada intervalo sem posição e liquida ao final com custos; registrar essa convenção, que não simula uma carteira continuamente carregada entre folds.

Walk-forward que recalibre em 2024 usando 2023 é outro experimento causal possível, mas não será apresentado como uma calibração congelada até 2022. Não misturar seus resultados com o desenho acima.

## Artefatos e aceite do planejamento

Gravar em `results/oos_audit/task1_spy/<run_id>/`:

- `manifest.json`: esquema, `status=planned|blocked`, cutoffs nominais/efetivos, última barra real, hashes de dados/configuração/código/especificação, SHA Git e estado dirty, versões Python/pacotes, seed, custos previstos, frequência, warmup/fronteiras, gaps, origem/ajustes conhecidos e lacunas. Incluir todos os flags de shadow mode e `dsr=null`, `pbo=null`, com motivo `not_computed_in_dry_run`.
- `coverage.csv`: ativo, datas, contagens IS/OOS, fonte e ajustes declarados/verificados, calendário/moeda quando comprovados, ausência/invalidade explícita. Ativo solicitado ausente bloqueia o lote, sem exclusão silenciosa.
- `folds.csv`: tipo de partição, fold, datas e contagens de treino, purge, teste e embargo; cada teste interno termina no IS. A reserva OOS fica identificada separadamente.

O `run_id` deve depender dos inputs/configuração/implementação, sem timestamp volátil; registrar horário da execução em campo separado. Não sobrescrever resultados históricos diferentes. Referência de desenho reutilizável: `src/automation/research.py` já faz hashes, cobertura e bloqueio sem promoção, mas seu corte 70/30 precisa ser substituído para esta tarefa.

Testes de aceitação em `tests/test_oos_validation.py`:

- corte por datas em feriados/limites de ano, preservando a primeira sessão disponível de 2023;
- nenhuma interseção de treino/purge/teste dentro do fold; todos os testes internos anteriores a 2023;
- dados ausentes, datas duplicadas, OHLC inválido e histórico insuficiente geram bloqueio explícito;
- mudar apenas preços OOS, mantendo datas, não altera índices/folds IS, mas altera o hash dos dados;
- mesmos inputs geram o mesmo plano/run_id; funções de backtest, otimização e rede substituídas por funções que falham comprovam que dry-run não as chama;
- nenhum Sharpe, DSR/PBO ou aprovação apresentado como calculado; todos os flags de pesquisa preservados.

Ao concluir, Antigravity registra comando, resumo dos testes, caminho do manifesto e ressalvas na caixa de mensagens. Parar nesse checkpoint, conforme o pedido de trabalho incremental; ChatGPT audita os artefatos antes da próxima pequena tarefa.

## Próximos incrementos da Fase 1

Após aceitar o plano: resolver proveniência/ajustes e política de purging; congelar grade/custos/seleção; executar o backtest de um ativo; preservar retornos líquidos por data/configuração e trades; depois calcular as estatísticas. O custo atual de 0,0015 por ponta é uma premissa do motor, não evidência de custo executável para qualquer tamanho de ordem. Taxa livre de risco e retorno de caixa também precisam ser explícitos.

DSR requer dispersão de Sharpes e contagem de tentativas, momentos dos retornos e frequência consistentes. Registrar busca anterior, Optuna e escolha entre ativos; a nova grade não representa todo o histórico. Sem ledger completo, marcar a limitação e análises condicionais, nunca inventar variância ou confiança. Referência: [Bailey e López de Prado, DSR (2014)](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

PBO não surge da média de quatro folds. Sua formulação CSCV usa uma matriz de retornos por alternativa/data e avalia a seleção IS contra o ranking complementar. CPCV e CSCV não são sinônimos; caminhos recombinados não devem ser chamados independentes sem prova. Planejar o diagnóstico de seleção no IS, sem transformar a reserva externa em calibrador. Referência: [Bailey et al., PBO (2015)](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

Sharpe consolidado deve vir da série de retornos consolidada com fronteiras/custos explícitos; não da média de Sharpes dos folds. WFE > 0,5 isolado não aprova uma estratégia. Nenhum DSR/PBO favorável basta para liberar capital real.

## Análise de ações e sequência posterior

NVDA, MSFT e VALE3.SA são **candidatos à análise**, ainda sem recomendação fundamentalista emitida nesta tarefa. A seleção terá memorando por ação: negócio e vantagem competitiva; crescimento e conversão em caixa; ROIC e dívida; valuation e expectativas embutidas no preço; cenários; antítese e catalisadores; liquidez, riscos e condições de revisão. Usar demonstrações e divulgações com data de disponibilidade, cotações datadas e fontes primárias. SPY e BIL exigem análise própria de ETFs, composição, custos e papel na carteira. Um backtest de momentum não substitui esse trabalho.

- **Fase 2 — HRP:** comparar pesos com 1/N e política vigente, preservando limites de concentração/caixa. Resolver antes BIL diário, ajustes, moeda-base/FX e calendários; considerar exposição sobreposta de SPY a NVDA/MSFT. HRP é um método de alocação por estrutura de risco, não prova de pesos ótimos ou de qualidade das empresas. [Artigo original de HRP](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678).
- **Fase 3 — Treasury 10 anos:** testar hipótese adicional em shadow mode. Distinguir z-score do nível de juros de choque/variação da taxa, fixar disponibilidade temporal e regra antes do teste, e comparar com overlay atual e sem overlay. Como 2022 motivou a hipótese, melhora em 2022 não é validação externa; não prometer blindagem definitiva.

Parecer deste checkpoint: **apto para implementar o planejamento temporal; não aprovado para inferência de alpha, recomendação de compra ou promoção ao capital real**. O documento de pesquisa é um conjunto de hipóteses; frases de garantia sobre HMM, filtros, HRP ou proteção macro não substituem validação.
