# Resultados gerados

Destino de checkpoints atômicos, métricas de grid search, estudos Optuna,
evidências walk-forward e relatórios de estresse. Resultados reproduzíveis
devem registrar configuração, hash dos dados, seed e versão do código.

## Evidências arquivadas nesta entrega

As subpastas `baseline/`, `global_research/`, `grid_search/`, `optuna/` e
`stress/` preservam resultados históricos de pesquisa. O arquivo
`manifesto_momentum.json` descreve a execução de 04/09/2026. Esses registros
não representam uma nova execução nem aprovação para uso de capital real.

`test_reports/pytest_report.xml` é o relatório histórico de 04/09/2026,
com 82 testes. Na verificação de publicação de 21/09/2026 passaram 133 testes
Python e 37 testes Node; os comandos e as limitações estão em
[`AGENT_SYNC.md`](../AGENT_SYNC.md).

Caches de mercado, bancos SQLite, checkpoints e saídas avulsas continuam
locais, conforme o [`.gitignore`](../.gitignore).
