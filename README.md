# LASTRO — fundo sistemático multi-sleeve

Backtest preliminar por proxies, reconstrução macro point-in-time, gate estatístico,
gráficos reprodutíveis e indicador de regime em modo shadow no TradingView.

## Relatório final

Entrega anônima, identificada apenas pela chave `AAKR`:

- `relatorios/AAKR.pdf` — 5 páginas, 16:9 horizontal (**o formato exigido pelo edital**);
- `relatorios/AAKR_retrato.pdf` — mesmo conteúdo em A4 retrato;
- `relatorios/AAKR.html` e `AAKR_retrato.html` — versões autocontidas, para revisão em tela.

O conteúdo vive em `relatorios/template_relatorio*.html`; as figuras entram embutidas
no momento da montagem. Nenhum arquivo entregue contém nome de equipe, de participante
ou de instituição.

## Executar

```bash
python -m pip install -r requirements.txt

python scripts/backtest_auditoria.py      # backtest por proxies + auditoria de vieses
python scripts/auditar_vintages_macro.py  # fotografias ALFRED disponíveis em cada mês
python scripts/diagnostico_overlay.py     # atribuição, sensibilidade e gate estatístico
python scripts/graficos_relatorio.py      # figuras R1..R7
python scripts/build_relatorio.py         # monta AAKR.pdf e AAKR_retrato.pdf
```

Para arquivar e reconciliar exportações mensais do TradingView sem preservar
colunas de outros indicadores do layout:

```bash
python scripts/auditar_tradingview.py --baa10y "caminho/BAA10Y.csv" --nfci "caminho/NFCI.csv"
```

O resultado sanitizado fica em `dados/tradingview/`; a trilha de auditoria, com
hashes dos arquivos brutos e o estado operacional vigente, fica em `resultados/`.

Dados em `dados/`; métricas, regressões, pesos, testes e imagens em `resultados/`.
Os manifests preservam a identidade das execuções por hash. O hash dá rastreabilidade,
mas não transforma a revisão exploratória em pré-registro ou holdout.

O registro de uso de IA generativa está em `log_uso_genai.csv`; cada nova intervenção
deve ser acrescentada no momento em que ocorrer.

## TradingView

O painel Pine v6 está em `tradingview/regime_credito_baa.pine`. Ele calcula o candidato
`BAA10Y` + `NFCI`, mas inicia com `Aprovar overlay para capital = false`. Nesse modo,
o regime continua visível e alertado enquanto os pesos executáveis permanecem
33,33% / 33,33% / 33,33%. O passo a passo e os limites operacionais estão em
`tradingview/README_EXPORTACAO_DADOS.md`.

## O que o teste valida

- vintages ALFRED disponíveis em cada fechamento mensal para `BAA10Y` e `NFCI`;
- z-score de 36 meses, histerese 1,0/0,5 e aplicação apenas em t+1;
- aplicação do sinal apenas no mês seguinte ao da observação;
- comparação Small Cap com e sem regime, e binário contra graduado;
- pesos 33/33/33 no normal e migração proporcional ao nível de de-risking;
- DSR, bootstrap em blocos, placebos circulares e erros HAC;
- verificações de datas, preços ajustados, dados ausentes e consistência retorno-peso.

## O que o teste ainda não valida

`VFMF` e o ETF small-cap escolhido são **proxies**. O backtest final precisa substituí-los
pelas seleções point-in-time dos Sleeves 1 e 2, com custos e turnover próprios. Enquanto
isso não acontecer, os números medem a arquitetura e o overlay — não o stock-picking.

## Diagnóstico e decisão de governança

`scripts/diagnostico_overlay.py` produz as evidências que o relatório usa:

| Evidência | Resultado |
|---|---|
| Auditoria de vintage | 2 de 102 decisões diferem do histórico final revisado |
| Atribuição contra o benchmark | overlay binário `-1,93 pp/ano`; proxies `-1,36 pp/ano` |
| Ponto cego de 2022 | z do crédito entre `-0,81` e `+0,32` enquanto o SPY caiu 23,93% |
| Sensibilidade (36 configurações) | 22% melhoram o drawdown; 0% melhoram o Sharpe |
| Evidência estatística | DSR 0,03%; IC95% ativo `[-6,84%; -0,22%]` |

A conclusão é operacional: `shadow_mode`, `aprovado=false`. O overlay permanece como
candidato de pesquisa; o capital não o executa até todos os gates e um teste futuro
congelado serem aprovados.

## Pipeline das seleções por ação

A lógica dos rankings e pesos por ação está em `quant_fund/`; consulte `README_QUANT.md`.
Para gerar números finais ainda é necessário completar preços, holdings e fundamentos
point-in-time dos universos.
