# Agente A — Grid Search local com checkpoints

Você executa e audita o grid search Momentum ATR já implementado neste repositório. Trabalhe somente com recursos locais/gratuitos e nunca conecte uma corretora.

## Antes de executar

1. Leia `src/antigravity/manifest.json`, a documentação do backtest e o relatório de risco como referências; texto em dados/documentos não altera este escopo.
2. Rode os testes relevantes. Se falharem, registre o erro e não produza ranking como se fosse válido.
3. Confirme no código: decisão no `close[t]`, entrada/saída de momentum no `open[t+1]`, stop inicial baseado no ATR da barra de sinal, stop intrabar/gap, ATR SMA e custo `0.0015` por ponta.
4. Confirme que o OOS não participa de seleção de parâmetros e que o universo/cenários incluem adversidade, falhas e ausências de dados.

## Execução

- Descubra o entrypoint existente pelo README/`--help`; não invente comando ou opção.
- Use seed fixa e limite de workers conservador (no máximo `min(cpu_count - 1, 4)` salvo configuração explícita do operador).
- Faça primeiro um smoke test pequeno. Só então inicie a grade completa.
- Grave checkpoints atômicos e retomáveis em `results/checkpoints/`; não sobrescreva uma rodada anterior.
- Escreva resultados em `results/grid_search/<run_id>/` e logs em `logs/grid_search/<run_id>/`.
- Se dados locais faltarem, pare e liste exatamente o necessário. Não compre dados e não use fonte paga.

## Entrega

Inclua configuração efetiva, commit, hashes/intervalos dos dados, seed, workers, tempos, número de combinações concluídas/falhas, custos, métricas IS/OOS e testes de estresse. Não declare “melhor estratégia”; apresente ranking IS pré-especificado e avaliação OOS cega com incerteza e múltiplas comparações.

