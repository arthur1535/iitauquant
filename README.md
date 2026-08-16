# LASTRO — fundo sistemático multi-sleeve

Backtest preliminar por proxies, suíte de auditoria, diagnóstico do overlay de risco,
gráficos reprodutíveis e o indicador de regime para TradingView.

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
python scripts/diagnostico_overlay.py     # atribuição, ponto cego, sensibilidade, seguro
python scripts/graficos_relatorio.py      # figuras R1..R7
python scripts/build_relatorio.py         # monta AAKR.pdf e AAKR_retrato.pdf
```

Dados em `dados/`; métricas, regressões, pesos, testes e imagens em `resultados/`.
Os parâmetros ficam congelados e identificados por hash em `resultados/manifesto_execucao.json`
e `resultados/manifesto_revisao.json`.

O registro de uso de IA generativa está em `log_uso_genai.csv`; cada nova intervenção
deve ser acrescentada no momento em que ocorrer.

## O que o teste valida

- z-score de 36 meses e histerese 1,0/0,5 nos dois eixos macro (`BAA10Y` e `NFCI`);
- aplicação do sinal apenas no mês seguinte ao da observação;
- comparação Small Cap com e sem regime, e binário contra graduado;
- pesos 33/33/33 no normal e migração proporcional ao nível de de-risking;
- métricas, drawdown, correlações e regressões FF5 + Momentum;
- verificações de datas, preços ajustados, dados ausentes e consistência retorno-peso.

## O que o teste ainda não valida

`VFMF` e o ETF small-cap escolhido são **proxies**. O backtest final precisa substituí-los
pelas seleções point-in-time dos Sleeves 1 e 2, com custos e turnover próprios. Enquanto
isso não acontecer, os números medem a arquitetura e o overlay — não o stock-picking.

## Diagnóstico que motivou a revisão do modelo

`scripts/diagnostico_overlay.py` produz as quatro evidências que o relatório usa:

| Evidência | Resultado |
|---|---|
| Atribuição contra o benchmark | overlay `−1,05 pp/ano`, mais que as duas seleções somadas |
| Ponto cego de 2022 | z do crédito entre `−0,77` e `+0,19` enquanto o mercado caiu 24% |
| Sensibilidade (36 configurações) | 100% melhoram o drawdown máximo; 44% melhoram o Sharpe |
| Overlay como seguro | prêmio cai de `−3,16` para `−1,33 pp/ano` com a mesma proteção de cauda |

A conclusão que daí resulta está implementada em `quant_fund/risk_overlay.py`: dois eixos
macro em vez de um, e migração graduada em vez de binária.

## Pipeline das seleções por ação

A lógica dos rankings e pesos por ação está em `quant_fund/`; consulte `README_QUANT.md`.
Para gerar números finais ainda é necessário completar preços, holdings e fundamentos
point-in-time dos universos.
