# Agente B — Testes da máquina de estados e do receiver

Você amplia e executa a suíte `pytest`. Pode escrever apenas em `tests/**` e `results/test_reports/**`. Não enfraqueça asserts para fazer testes passarem e não modifique código de produção; reporte o defeito com um caso mínimo quando necessário.

## Casos obrigatórios do backtest

- Momentum usa apenas `close[t]`; uma entrada sinalizada em `t` recebe preço `open[t+1]`.
- Stop inicial usa `entry_open - multiplier × ATR[t_sinal]`.
- Gap com `open <= stop` sai no `open`; toque com `open > stop` e `low <= stop` sai no stop/hipótese de slippage configurada.
- Ratchet é `max(stop anterior, close - multiplier × ATR)` e nunca recua.
- Saída por momentum em `t` preenche em `open[t+1]`.
- Custos são `0.0015` na entrada e `0.0015` na saída, sem dupla contagem.
- Dados insuficientes, NaN, zero/negativo, série curta e posição aberta no fim têm comportamento explícito.

## Casos obrigatórios do receiver

- HMAC correto sobre corpo bruto retorna `200`; ausente, malformado ou incorreto retorna `401`.
- Segredo ausente/curto impede readiness/start seguro.
- Replay, timestamp fora da janela e duplicata de `idempotency_key` não criam nova ordem.
- Ações/motivos incompatíveis, ticker fora da allowlist, quantidade/preço inválidos e campos malformados são rejeitados.
- Kill switch impede aceitação operacional; persistência SQLite registra decisão sem guardar segredo.
- Não existe import/chamada de SDK de broker real.

Use diretórios temporários, relógio injetável/fixo e fixtures OHLC mínimas. Rode a suíte completa ao final e grave JUnit XML se o projeto já suportar essa opção. Relate testes aprovados, falhos e não executados; não esconda warnings.

